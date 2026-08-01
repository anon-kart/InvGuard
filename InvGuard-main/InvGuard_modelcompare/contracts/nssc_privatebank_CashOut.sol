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
        if (_am <= balances[msg.sender]) {
            (bool ok, ) = msg.sender.call{value: _am}("");
            if (ok) {
                unchecked { balances[msg.sender] -= _am; }   // CEI violation: state update AFTER call
                TransferLog.AddMessage(msg.sender, _am, "CashOut");
            }
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
