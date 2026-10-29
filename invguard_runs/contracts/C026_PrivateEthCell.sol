pragma solidity ^0.4.24;

contract Log {
    struct Message {
        address sender;
        string data;
        uint256 val;
        uint256 time;
    }

    Message[] public history;

    function addMessage(address adr, uint256 val, string data) public {
        history.push(Message(adr, data, val, now));
    }
}

contract PrivateEthCell {
    mapping(address => uint256) public balances;
    uint256 public minDeposit = 1 ether;
    Log transferLog;

    constructor(address log) public {
        transferLog = Log(log);
    }

    function deposit() public payable {
        require(msg.value >= minDeposit);
        balances[msg.sender] += msg.value;
        transferLog.addMessage(msg.sender, msg.value, "Deposit");
    }

    function cashOut(uint256 amount) public {
        require(amount <= balances[msg.sender]);
        balances[msg.sender] -= amount;
        msg.sender.call.value(amount)();
        transferLog.addMessage(msg.sender, amount, "CashOut");
    }
}
