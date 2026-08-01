// SPDX-License-Identifier: UNLICENSED
// Real-world honeypot: Private_Bank reentrancy (Trail of Bits NSSC).
// Exploit preserved on 0.8 via unchecked decrement after external call.
pragma solidity ^0.8.19;

contract Private_Bank {
    mapping(address => uint) public balances;
    uint public MinDeposit = 1 ether;
    Log TransferLog;

    constructor(address _log) { TransferLog = Log(_log); }

    function Deposit() public payable {
        if (msg.value >= MinDeposit) {
            balances[msg.sender] += msg.value;
            TransferLog.AddMessage(msg.sender, msg.value, "Deposit");
        }
    }

    function CashOut(uint _am) public {
        require(_am <= balances[msg.sender], "Insufficient balance");
        balances[msg.sender] -= _am; // Move state update before external call
        (bool ok, ) = msg.sender.call{value: _am}("");
        if (ok) {
            TransferLog.AddMessage(msg.sender, _am, "CashOut");
        } else {
            balances[msg.sender] += _am; // Revert state change if call fails
        }
    }

    receive() external payable {}
}

contract Log {
    struct Message { address Sender; string Data; uint Val; uint Time; }
    Message[] public History;
    Message LastMsg;
    function AddMessage(address _adr, uint _val, string memory _data) public {
        LastMsg.Sender = _adr;
        LastMsg.Time = block.timestamp;
        LastMsg.Val = _val;
        LastMsg.Data = _data;
        History.push(LastMsg);
    }
}