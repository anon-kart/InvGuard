pragma solidity >= 0.5.0 < 0.6.0;

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address who) external view returns (uint256);
    function transfer(address to, uint256 value) external returns (bool);
    event Transfer(address indexed from, address indexed to, uint256 value);
}

contract PHO is IERC20 {
  mapping(address => uint) balances_intou26;

function transfer_intou26(address _to, uint _value) public returns (bool) {
    require(balances_intou26[msg.sender] - _value >= 0);
    balances_intou26[msg.sender] -= _value;
    balances_intou26[_to] += _value;
    return true;
  }
  string public name = "PHO";
  uint8 public decimals = 18;
  uint256 saleAmount;
  uint256 evtAmount;
  uint256 teamAmount;
  uint256 _totalSupply;
  mapping(address => uint) balances;
  address public owner;
  address public sale;
  address public evt;
  address public team;

    modifier isOwner {
        require(owner == msg.sender);
        _;
    }

    constructor() public {
        owner   = msg.sender;
        sale    = 0x071F73f4D0befd4406901AACE6D5FFD6D297c561;
        evt     = 0x76535ca5BF1d33434A302e5A464Df433BB1F80F6;
        team    = 0xD7EC5D8697e4c83Dc33D781d19dc2910fB165D5C;

        saleAmount    = toWei(1000000000);
        evtAmount     = toWei(200000000);
        teamAmount    = toWei(800000000);
        _totalSupply  = toWei(2000000000);

        require(_totalSupply == saleAmount + evtAmount + teamAmount);

        balances[owner] = _totalSupply;
        emit Transfer(address(0), owner, balances[owner]);

        transfer(sale, saleAmount);
        transfer(evt, evtAmount);
        transfer(team, teamAmount);
        require(balances[owner] == 0);
    }

    function totalSupply() public view returns (uint) {
        return _totalSupply;
    }

    function balanceOf(address who) public view returns (uint256) {
        return balances[who];
    }

    function transfer(address to, uint256 value) public returns (bool success) {
        require(msg.sender != to);
        require(value > 0);

        require( balances[msg.sender] >= value );
        require( balances[to] + value >= balances[to] );

        if(msg.sender == team) {
            require(now >= 1589036400);
            if(balances[msg.sender] - value < toWei(600000000))
                require(now >= 1620572400);
            if(balances[msg.sender] - value < toWei(400000000))
                require(now >= 1652108400);
            if(balances[msg.sender] - value < toWei(200000000))
                require(now >= 1683644400);
        }

        balances[msg.sender] -= value;
        balances[to] += value;

        emit Transfer(msg.sender, to, value);
        return true;
    }

    function burnCoins(uint256 value) public {
        require(balances[msg.sender] >= value);
        require(_totalSupply >= value);

        balances[msg.sender] -= value;
        _totalSupply -= value;

        emit Transfer(msg.sender, address(0), value);
    }

    function toWei(uint256 value) private view returns (uint256) {
        return value * (10 ** uint256(decimals));
    }
}
